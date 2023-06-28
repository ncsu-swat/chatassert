package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import java.util.ArrayList;
import java.util.List;

import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.ast.expr.MethodCallExpr;

public class PrefixInjectionTransformer extends VoidVisitorAdapter<Void> {

    String original, methodNotFound;
    List<String> replacements = new ArrayList<String>();

    PrefixInjectionTransformer(String assertion, String methodNotFound) {
        this.original = assertion;
        this.methodNotFound = methodNotFound;
    }

    @Override
    public void visit(final MethodCallExpr n, final Void arg) {
        super.visit(n, arg);

        String methodNameToCheck = n.toString().substring(0, n.toString().indexOf("("));

        if(methodNameToCheck.equals(methodNotFound)){
            String s = original.replaceAll(methodNotFound, "<insert>."+methodNotFound);
            addReplacement(s);
        }
    }

    private void addReplacement(String s) {
        if (s.contains("<insert>")) {
            replacements.add(s);
        }
    }
}