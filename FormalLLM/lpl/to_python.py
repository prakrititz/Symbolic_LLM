from FormalLLM.lspec.ast import *
from FormalLLM.lpl.ast import *


def expr_to_python(expr: Expr) -> str:
    if isinstance(expr, BinaryOp):
        op = expr.op
        if op == "/\\":
            op = "and"
        elif op == "\\/":
            op = "or"
        elif op == "=":
            op = "=="
        elif op == "<>":
            op = "!="
        
        return f"({expr_to_python(expr.left)} {op} {expr_to_python(expr.right)})"
    elif isinstance(expr, UnaryOp):
        op = expr.op
        if op == "~":
            op = "not "
        return f"({op}{expr_to_python(expr.expr)})"
    elif isinstance(expr, Variable):
        return expr.name
    elif isinstance(expr, Const):
        return expr.name
    elif isinstance(expr, Number):
        return str(expr.value)
    elif isinstance(expr, BooleanConst):
        return str(expr.value)
    elif isinstance(expr, VariablePreviousState):
        return f"{expr.name}0"
    elif isinstance(expr, ArraySelect):
        return f"{expr.array}[{expr_to_python(expr.index)}]"
    elif isinstance(expr, ArraySlice):
        return f"{expr.array}[{expr_to_python(expr.start)}:{expr_to_python(expr.end)}]"
    elif isinstance(expr, QuantifiedExpr):
        raise NotImplementedError(f"Execution of quantified expressions ({expr.quantifier}) is not supported in plain Python without explicit bounded domains.")
    else:
        raise ValueError(f"Unknown expression type in to_python: {type(expr)}")


def to_python(node: MixNode, indent: int = 0) -> str:
    if isinstance(node, Spec):
        raise ValueError("Cannot execute unresolved Spec node")
    
    pad = "    " * indent
    if isinstance(node, Skip):
        return f"{pad}pass"
    elif isinstance(node, Assignment):
        return f"{pad}{node.variable} = {expr_to_python(node.expr)}"
    elif isinstance(node, SequentialComposition):
        return f"{to_python(node.first, indent)}\n{to_python(node.second, indent)}"
    elif isinstance(node, IfElse):
        out = f"{pad}if {expr_to_python(node.guard)}:\n"
        out += to_python(node.then_branch, indent + 1) + "\n"
        out += f"{pad}else:\n"
        out += to_python(node.else_branch, indent + 1)
        return out
    elif isinstance(node, While):
        out = f"{pad}while {expr_to_python(node.guard)}:\n"
        out += to_python(node.body, indent + 1)
        return out
    elif node is None:
        # Handle cases where parsing might yield None temporarily
        return f"{pad}pass"
    else:
        raise ValueError(f"Unknown L_pl node type in to_python: {type(node)}")
