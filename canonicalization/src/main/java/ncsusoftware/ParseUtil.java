package ncsusoftware;

import java.util.Optional;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.SimpleName;

public class ParseUtil {

    // factory method for expressions
    public static Expression parseExpr(String s) {
        JavaParser jparser = new JavaParser();
        Optional<Expression> optStmt = jparser.parseExpression(s).getResult();
        if (optStmt.isPresent()) {
            Expression expr = (Expression) optStmt.get();
            return expr;
        }
        throw new RuntimeException("should not happen!");
    }

    // for debugging
    public static void printTypesContentsRecursively(Node node) {
        System.out.printf("%s: %s\n", node.toString(), node.getClass());
        for (Node n : node.getChildNodes()) {
            printTypesContentsRecursively(n);
        }
    }

    // write one of this as neeed 
    public static void replaceThisNodeWithThatNode_FieldAccessExpr(FieldAccessExpr parent, Node source, Node target) {
        if (parent.getScope()==source) {
            parent.setScope((Expression)target);
            return;
        } else if (parent.getName()==source) {
            parent.setName((SimpleName)target);
            return;
        }
        throw new RuntimeException("should not reach this point; check other fields");
    }

    public static void replaceThisNodeWithThatWithinParent(Node source, Node target) {
        Node parent = source.getParentNode().get();
        if (parent instanceof FieldAccessExpr) {
            replaceThisNodeWithThatNode_FieldAccessExpr((FieldAccessExpr) parent, source, target);
            return;
        }
        throw new RuntimeException("TODO");
    }
        
}
