package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

import com.github.javaparser.ast.expr.AssignExpr;
import com.github.javaparser.ast.body.VariableDeclarator;

public class AssignExprVisitor extends VoidVisitorAdapter<Void> {
    Map<String, String> lhs2rhs = new HashMap<String, String>();

    @Override
    public void visit(final AssignExpr n, final Void arg) {
        super.visit(n, arg);
        lhs2rhs.put(n.getValue().toString(), n.getTarget().toString());
    }

    @Override
    public void visit(final VariableDeclarator n, final Void arg) {
        super.visit(n, arg);
        lhs2rhs.put(n.getInitializer().get().toString(), n.getName().toString());
    }
}