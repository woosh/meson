# Copyright 2012 Jussi Pakkanen

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ply.lex as lex
import ply.yacc as yacc
import nodes
from coredata import MesonException

class ParserException(MesonException):
    def __init__(self, text, lineno):
        MesonException.__init__(self, text)
        self.lineno = lineno

reserved = {'true' : 'TRUE',
            'false' : 'FALSE',
            'if' : 'IF',
            'endif' : 'ENDIF',
            'else' : 'ELSE',
            'and' : 'AND',
            'or' : 'OR',
            'not' : 'NOT',
            }

tokens = ['LPAREN',
          'RPAREN',
          'LBRACKET',
          'RBRACKET',
          'ATOM',
          'COMMENT',
          'ASSIGN',
          'EQUALS',
          'NEQUALS',
          'COMMA',
          'DOT',
          'STRING',
          'MULTILINE_STRING',
          'INT',
          'EOL_CONTINUE',
          'EOL',
          'COLON',
          ] + list(reserved.values())

t_ASSIGN = '='
t_EQUALS = '=='
t_NEQUALS = '\!='
t_LPAREN = '\('
t_RPAREN = '\)'
t_LBRACKET = '\['
t_RBRACKET = '\]'
t_ignore_COMMENT = '\\#.*?(?=\\n)'
t_COMMA = ','
t_DOT = '\.'
t_COLON = ':'

t_ignore = ' \t'

precedence = (
('left', 'COMMA'),
('left', 'ASSIGN'),
('nonassoc', 'EQUALS', 'NEQUALS'),
('left', 'OR'),
('left', 'AND'),
('nonassoc', 'COLON'),
('left', 'DOT'),
)

def t_ATOM(t):
    '[a-zA-Z][_0-9a-zA-Z]*'
    t.type = reserved.get(t.value, 'ATOM')
    return t


def t_MULTILINE_STRING(t):
    r"'''(.|\n)*?'''"
    t.value = t.value[3:-3]
    t.lexer.lineno += t.value.count('\n')
    return t

def t_STRING(t):
    "'[^']*'"
    t.value = t.value[1:-1]
    return t

def t_INT(t):
    '[0-9]+'
    t.value = int(t.value)
    return t

def t_EOL(t):
    r'\n'
    t.lexer.lineno += 1
    return t

def t_EOL_CONTINUE(t):
    r'\\[ \t]*\n'
    t.lexer.lineno += 1

def t_error(t):
    raise ParserException("Illegal character '%s'." % t.value[0], t.lineno)

# Yacc part

def p_codeblock(t):
    'codeblock : statement EOL codeblock'
    cb = t[3]
    cb.prepend(t[1])
    t[0] = cb
    
def p_codeblock_emptyline(t):
    'codeblock : EOL codeblock'
    t[0] = t[2]

def p_codeblock_last(t):
    'codeblock : statement EOL'
    cb = nodes.CodeBlock(t[1].lineno())
    cb.prepend(t[1])
    t[0] = cb

def p_expression_atom(t):
    'expression : ATOM'
    t[0] = nodes.AtomExpression(t[1], t.lineno(1))

def p_expression_int(t):
    'expression : INT'
    t[0] = nodes.IntExpression(t[1], t.lineno(1))

def p_expression_bool(t):
    '''expression : TRUE
                  | FALSE'''
    if t[1] == 'true':
        t[0] = nodes.BoolExpression(True, t.lineno(1))
    else:
        t[0] = nodes.BoolExpression(False, t.lineno(1))

def p_expression_string(t):
    'expression : STRING'
    t[0] = nodes.StringExpression(t[1], t.lineno(1))

def p_expression_multiline_string(t):
    'expression : MULTILINE_STRING'
    t[0] = nodes.StringExpression(t[1], t.lineno(1))

def p_statement_assign(t):
    'statement : expression ASSIGN statement'
    t[0] = nodes.Assignment(t[1], t[3], t[1].lineno())

def p_statement_comparison(t):
    '''statement : statement EQUALS statement
                 | statement NEQUALS statement'''
    t[0] = nodes.Comparison(t[1], t[2], t[3], t[1].lineno())

def p_statement_array(t):
    '''statement : LBRACKET args RBRACKET
                 | LBRACKET EOL args RBRACKET'''
    if len(t) == 4:
        t[0] = nodes.ArrayStatement(t[2], t.lineno(1))
    else:
        t[0] = nodes.ArrayStatement(t[3], t.lineno(1))

def p_statement_array2(t):
    '''statement : LBRACKET args EOL RBRACKET
                 | LBRACKET EOL args EOL RBRACKET'''
    if len(t) == 5:
        t[0] = nodes.ArrayStatement(t[2], t.lineno(1))
    else:
        t[0] = nodes.ArrayStatement(t[3], t.lineno(1))

def p_statement_func_call(t):
    'statement : expression LPAREN args RPAREN'
    t[0] = nodes.FunctionCall(t[1], t[3], t[1].lineno())

def p_statement_method_call(t):
    'statement : statement DOT expression LPAREN args RPAREN'
    t[0] = nodes.MethodCall(t[1], t[3], t[5], t[1].lineno())

def p_statement_if(t):
    'statement : IF statement EOL codeblock elseblock ENDIF'
    t[0] = nodes.IfStatement(t[2], t[4], t[5], t.lineno(1))

def p_statement_parentheses(t):
    'statement : LPAREN statement RPAREN'
    t[0] = t[2]

def p_statement_and(t):
    'statement : statement AND statement'
    t[0] = nodes.AndStatement(t[1], t[3])

def p_statement_or(t):
    'statement : statement OR statement'
    t[0] = nodes.OrStatement(t[1], t[3])

def p_empty_else(t):
    'elseblock : '
    return None

def p_else(t):
    'elseblock : ELSE EOL codeblock'
    t[0] = t[3]

def p_statement_expression(t):
    'statement : expression'
    t[0] = nodes.statement_from_expression(t[1])


def p_args_multiple(t):
    '''args : statement COMMA args
            | statement COMMA EOL args
            | statement EOL COMMA args'''
    if len(t) == 5:
        args = t[4]
    else:
        args = t[3]
    args.prepend(t[1])
    t[0] = args

def p_kwargs_multiple(t):
    '''args : expression COLON statement COMMA args
            | expression COLON statement COMMA EOL args
            | expression COLON statement EOL COMMA args'''
    if len(t) == 7:
        args = t[6]
    else:
        args = t[5]
    args.set_kwarg(t[1], t[3])
    t[0] = args

def p_args_single_pos(t):
    'args : statement'
    args = nodes.Arguments(t[1].lineno())
    args.prepend(t[1])
    t[0] = args

def p_args_single_kw(t):
    'args : expression COLON statement'
    a = nodes.Arguments(t[1].lineno())
    a.set_kwarg(t[1], t[3])
    t[0] = a

def p_args_none(t):
    'args :'
    t[0] = nodes.Arguments(t.lineno(0))

def p_error(t):
    lineno = -1
    if t is None:
        txt = 'NONE'
    else:
        txt = t.value
        lineno = t.lineno
    raise ParserException('Parser errored out at: %s.' % txt, lineno)

def test_lexer():
    s = """hello = (something) # this = (that)
    two = ['file1', 'file2']
    function(h) { stuff }
    obj.method(lll, \\ 
    'string')
    """
    lexer = lex.lex()
    lexer.input(s)
    while True:
        tok = lexer.token()
        if not tok:
            break
        print(tok)

def generate_parser_files(outputdir):
    code = """project('empty', 'c')
"""
    build_ast(code, outputdir=outputdir)

def build_ast(code, outputdir=None):
    code = code.rstrip() + '\n'
    lex.lex()
    if outputdir:
        parser = yacc.yacc(outputdir=outputdir)
    else:
        parser = yacc.yacc()
    result = parser.parse(code)
    return result
