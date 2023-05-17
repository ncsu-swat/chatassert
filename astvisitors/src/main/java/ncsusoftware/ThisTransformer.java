package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.stmt.ExpressionStmt;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.FieldAccessExpr;

public class ThisTransformer extends VoidVisitorAdapter<Void> {

    /**
     * Abitrary transformation: this.e ==> e
     */

    @Override
    public void visit(FieldAccessExpr faexpr, Void arg) {
        super.visit(faexpr, arg);
        String s = faexpr.toString();
        if (s.startsWith("this")) {
            // create new AST newExp
            String smod = s.substring("this.".length());
            Expression newExp = ParseUtil.parseExpr(smod);
            ParseUtil.replaceThisNodeWithThatWithinParent(faexpr, newExp);
        }
    }

    public void visitStmt(com.github.javaparser.ast.stmt.Statement stmt) {
        if (!(stmt instanceof ExpressionStmt))
            throw new RuntimeException("missing case; please expand for " + stmt.getClass());
        ExpressionStmt estmt = (ExpressionStmt)stmt;
        visit(estmt, null);
    }

}