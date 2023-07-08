package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import java.util.ArrayList;
import java.util.List;

import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.ast.expr.MethodCallExpr;

public class PrefixHoleInjectionTransformer extends VoidVisitorAdapter<Void> {

    String original, methodNotFound;
    List<String> replacements = new ArrayList<String>();

    PrefixHoleInjectionTransformer(String assertion, String methodNotFound) {
        this.original = assertion;
        this.methodNotFound = methodNotFound;
    }

    @Override
    public void visit(final MethodCallExpr n, final Void arg) {
        super.visit(n, arg);

        if(n.getName().asString().equals(methodNotFound)){
            this.original = this.original.replaceAll(" ", "");
            String scope = n.getScope().get().toString();
            scope = scope.replaceAll("\\.", "~");

            String s = this.original.replaceAll("\\.", "~");
            while(s.contains(scope)){
                s = s.replace(scope, "<insert>");
            }
            s = s.replaceAll("~", ".");
            
            addReplacement(s);
        }
    }

    private void addReplacement(String s) {
        if (s.contains("<insert>")) {
            replacements.add(s);
        }
    }
}