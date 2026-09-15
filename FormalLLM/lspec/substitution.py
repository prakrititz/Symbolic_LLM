import copy
from typing import Set
from .ast import *

def get_free_vars(node: ASTNode, bound_vars: Set[str] = None) -> Set[str]:
    if bound_vars is None: bound_vars = set()
    free_vars = set()
    
    if isinstance(node, Variable) or isinstance(node, Const):
        if node.name not in bound_vars:
            free_vars.add(node.name)
    elif isinstance(node, Definition) or isinstance(node, QuantifiedExpr):
        new_bound = bound_vars.copy()
        for p in node.params:
            new_bound.add(p.name)
        free_vars.update(get_free_vars(node.expr, new_bound))
    elif isinstance(node, BinaryOp):
        free_vars.update(get_free_vars(node.left, bound_vars))
        free_vars.update(get_free_vars(node.right, bound_vars))
    elif isinstance(node, UnaryOp):
        free_vars.update(get_free_vars(node.expr, bound_vars))
    elif isinstance(node, ArraySelect):
        if node.array not in bound_vars:
            free_vars.add(node.array)
        free_vars.update(get_free_vars(node.index, bound_vars))
    elif isinstance(node, ArraySlice):
        if node.array not in bound_vars:
            free_vars.add(node.array)
        free_vars.update(get_free_vars(node.start, bound_vars))
        free_vars.update(get_free_vars(node.end, bound_vars))
    elif isinstance(node, Spec):
        free_vars.update(get_free_vars(node.precondition, bound_vars))
        free_vars.update(get_free_vars(node.postcondition, bound_vars))
        
    return free_vars

def alpha_rename(node: ASTNode, old_name: str, new_name: str) -> ASTNode:
    if isinstance(node, Definition):
        params = [Param(new_name if p.name == old_name else p.name, p.type_) for p in node.params]
        return Definition(node.name, params, alpha_rename(node.expr, old_name, new_name))
    elif isinstance(node, QuantifiedExpr):
        params = [Param(new_name if p.name == old_name else p.name, p.type_) for p in node.params]
        return QuantifiedExpr(node.quantifier, params, alpha_rename(node.expr, old_name, new_name))
    elif isinstance(node, Variable):
        return Variable(new_name) if node.name == old_name else Variable(node.name)
    elif isinstance(node, Const):
        return Const(new_name) if node.name == old_name else Const(node.name)
    elif isinstance(node, BinaryOp):
        return BinaryOp(alpha_rename(node.left, old_name, new_name), node.op, alpha_rename(node.right, old_name, new_name))
    elif isinstance(node, UnaryOp):
        return UnaryOp(node.op, alpha_rename(node.expr, old_name, new_name))
    elif isinstance(node, ArraySelect):
        arr = new_name if node.array == old_name else node.array
        return ArraySelect(arr, alpha_rename(node.index, old_name, new_name))
    elif isinstance(node, ArraySlice):
        arr = new_name if node.array == old_name else node.array
        return ArraySlice(arr, alpha_rename(node.start, old_name, new_name), alpha_rename(node.end, old_name, new_name))
    elif isinstance(node, Spec):
        return Spec(alpha_rename(node.precondition, old_name, new_name), alpha_rename(node.postcondition, old_name, new_name))
    return copy.deepcopy(node)


def substitute(node: ASTNode, var_name: str, replacement: Expr) -> ASTNode:
    """
    Substitutes occurrences of `var_name` with `replacement` in the `node`.
    Returns a new ASTNode with substitutions applied, applying alpha-renaming 
    to avoid capture of free variables in `replacement`.
    """
    if isinstance(node, Spec):
        return Spec(
            substitute(node.precondition, var_name, replacement),
            substitute(node.postcondition, var_name, replacement)
        )
        
    elif isinstance(node, Definition):
        if any(p.name == var_name for p in node.params):
            return copy.deepcopy(node) # Shadowed
        
        expr = node.expr
        repl_free_vars = get_free_vars(replacement)
        for p in node.params:
            if p.name in repl_free_vars:
                # Alpha rename to avoid capture
                fresh = f"{p.name}_fresh"
                expr = alpha_rename(expr, p.name, fresh)
                p.name = fresh # Rename the param itself for the returned node
                
        return Definition(
            node.name,
            copy.deepcopy(node.params),
            substitute(expr, var_name, replacement)
        )
        
    elif isinstance(node, QuantifiedExpr):
        if any(p.name == var_name for p in node.params):
            return copy.deepcopy(node) # Shadowed
            
        expr = node.expr
        new_params = copy.deepcopy(node.params)
        repl_free_vars = get_free_vars(replacement)
        for p in new_params:
            if p.name in repl_free_vars:
                # Alpha rename
                fresh = f"{p.name}_fresh"
                expr = alpha_rename(expr, p.name, fresh)
                p.name = fresh
                
        return QuantifiedExpr(
            node.quantifier,
            new_params,
            substitute(expr, var_name, replacement)
        )
        
    elif isinstance(node, BinaryOp):
        return BinaryOp(
            substitute(node.left, var_name, replacement),
            node.op,
            substitute(node.right, var_name, replacement)
        )
        
    elif isinstance(node, UnaryOp):
        return UnaryOp(
            node.op,
            substitute(node.expr, var_name, replacement)
        )
        
    elif isinstance(node, Variable):
        if node.name == var_name:
            return copy.deepcopy(replacement)
        return Variable(node.name)
        
    elif isinstance(node, Const):
        if node.name == var_name:
            return copy.deepcopy(replacement)
        return Const(node.name)
        
    elif isinstance(node, VariablePreviousState):
        return VariablePreviousState(node.name)
        
    elif isinstance(node, Number):
        return Number(node.value)
        
    elif isinstance(node, BooleanConst):
        return BooleanConst(node.value)
        
    elif isinstance(node, ArraySelect):
        return ArraySelect(
            replacement if node.array == var_name and isinstance(replacement, str) else node.array, # Simplified array name sub
            substitute(node.index, var_name, replacement)
        )
        
    elif isinstance(node, ArraySlice):
        return ArraySlice(
            replacement if node.array == var_name and isinstance(replacement, str) else node.array,
            substitute(node.start, var_name, replacement),
            substitute(node.end, var_name, replacement)
        )
        
    return copy.deepcopy(node)
