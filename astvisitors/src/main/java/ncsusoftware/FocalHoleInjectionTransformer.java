package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import java.util.ArrayList;
import java.util.List;

import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.ast.expr.MethodCallExpr;

public class FocalHoleInjectionTransformer extends VoidVisitorAdapter<Void> {
    
    String original;
    List<String> replacements = new ArrayList<String>();

    FocalHoleInjectionTransformer(String assertion) {
        this.original = assertion;
    }

    @Override
    public void visit(final SimpleName n, final Void arg) {
        super.visit(n, arg);

        String checkFocal = n.asString().toLowerCase();
        String s = n.asString();

        if(checkFocal.contains("focal")){
            s = original.replace(n.asString(), "<insert>");
        }

        addReplacement(s);
    }

    private void addReplacement(String s) {
        if (s.contains("<insert>")) {
            replacements.add(s);
        }
    }
}