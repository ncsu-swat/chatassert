package ncsusoftware;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.expr.Expression;
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

        String s = "";
        if(n.getName().asString().equals(methodNotFound)){
            this.original = this.original.replaceAll(" ", "");
            Optional<Expression> scopeExpr = n.getScope();
            if(scopeExpr.isPresent()){
                String scope = scopeExpr.get().toString();
                scope = scope.replaceAll("\\.", "~");

                s = this.original.replaceAll("\\.", "~");
                while(s.contains(scope)){
                    s = s.replace(scope, "<insert>");
                }
                s = s.replaceAll("~", ".");
            }else{
                s = this.original.replace(n.toString(), "<insert>." + n.toString());
            }
            
            addReplacement(s);
        }
    }

    private void addReplacement(String s) {
        if (s.contains("<insert>")) {
            replacements.add(s);
        }
    }
}