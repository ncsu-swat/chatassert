# This class is obtained from teco.data.structures.py (link: https://github.com/EngineeringSoftware/teco/blob/main/python/teco/data/structures.py)
# Added pretty_print
import re
import enum
from typing import Callable, Iterable, List, Optional, Tuple

class TraverseOrder(enum.Enum):
    PRE_ORDER = "pre_order"
    DEPTH_FIRST = "dfs"

class AST:
    ast_type: str = ""
    tok_kind: Optional[str] = None
    tok: Optional[str] = None
    children: Optional[List["AST"]] = None
    lineno: str = None

    @classmethod
    def deserialize(cls, data: list) -> "AST":
        ast = cls()

        type_and_kind = data[0]
        ast.lineno = data[1]
        if ":" in type_and_kind:
            # terminal
            ast.ast_type, ast.tok_kind = type_and_kind.split(":")
            ast.tok = data[2]
        else:
            # non-terminal
            ast.ast_type = type_and_kind
            ast.children = [cls.deserialize(child) for child in data[2:]]
        return ast

    def serialize(self) -> list:
        if self.tok_kind is not None:
            # terminal
            return [f"{self.ast_type}:{self.tok_kind}", self.lineno, self.tok]
        else:
            # non-terminal
            return [self.ast_type, self.lineno] + [
                child.serialize() for child in self.children
            ]

    def __str__(self, indent: int = 0):
        s = self.ast_type
        if self.tok is not None:
            s += f"|{self.tok_kind}[{self.tok}]"
        if self.lineno is not None:
            s += f" <{self.lineno}>"
        if self.children is not None:
            s += " (\n" + " " * indent
            for child in self.children:
                s += "  " + child.__str__(indent + 2) + "\n" + " " * indent
            s += ")"
        return s

    def pretty_print(self, indent: int = 0):
        prev = ''
        s = ''
        if self.tok_kind is not None:
            s += self.tok + " "
            if self.tok in [';', '{']: s += '\n'
            prev = self.tok_kind
        if self.children is not None and self.ast_type not in ['MarkerAnnotationExpr']:
            for child in self.children:
                s += child.pretty_print(indent + 2)
        return " " * indent + re.sub(' +', ' ', s)

    def get_methodName(self):
        if self.ast_type in ['MethodDeclaration']:
            for child in self.children:
                if child.ast_type in ['SimpleName']:
                    return child.tok
        return "setUp"

    def get_lineno_range(self) -> Tuple[int, int]:
        if self.lineno is None:
            raise RuntimeError("AST has no line number")
        if "-" in self.lineno:
            start, end = self.lineno.split("-")
            return int(start), int(end)
        else:
            return int(self.lineno), int(self.lineno)

    def is_terminal(self) -> bool:
        return self.children is None

    def traverse(
        self,
        stop_func: Callable[["AST"], bool] = lambda x: False,
        order: TraverseOrder = TraverseOrder.DEPTH_FIRST,
    ) -> Iterable["AST"]:
        """Traverse over each node in pre-order"""
        queue = [self]
        while len(queue) > 0:
            cur = queue.pop(0)
            yield cur

            if not stop_func(cur):
                if cur.children is not None:
                    if order == TraverseOrder.PRE_ORDER:
                        queue += cur.children
                    elif order == TraverseOrder.DEPTH_FIRST:
                        queue = cur.children + queue
                    else:
                        raise ValueError(f"Unknown traverse order: {order}")

    def get_tokens(self) -> List[str]:
        tokens = []
        for n in self.traverse():
            if n.is_terminal():
                tokens.append(n.tok)
        return tokens

    # def get_insns(self) -> List[Insn]:
    #     if self.insns is None:
    #         return []
    #     return [Insn(insn) for insn in self.insns]

    def get_body(self) -> "AST":
        """Extract the method body of this method declaration, which is always a BlockStmt node"""
        # find first BlockStmt in child
        block_stmt = None
        for child in self.children:
            if child.ast_type == "BlockStmt":
                block_stmt = child

        if block_stmt is None:
            raise RuntimeError("Method has no body")

        return block_stmt

    def get_sign(self) -> "AST":
        """Extract the sub-tree for the method signature (excluding method body, opening and closing parens)"""
        copy_node = copy.copy(self)
        copy_node.children = []

        for child in self.children:
            # stop at first block statement
            if child.ast_type == "BlockStmt":
                break
            copy_node.children.append(child)
        return copy_node

    def size(self, count_terminal: bool = True, count_nonterminal: bool = True) -> int:
        c = 0
        if self.is_terminal():
            if count_terminal:
                c += 1
        else:
            if count_nonterminal:
                c += 1
            for child in self.children:
                c += child.size(count_terminal, count_nonterminal)
        return c