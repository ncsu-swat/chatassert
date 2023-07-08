package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.HashSet;

import com.github.javaparser.ast.expr.SimpleName;
import com.github.javaparser.ast.expr.MethodCallExpr;

public class VariableHoleInjectionTransformer extends VoidVisitorAdapter<Void> {

    String original, variableNotFound;
    Set<String> doneSet = new HashSet<>();
    List<String> replacements = new ArrayList<String>();

    VariableHoleInjectionTransformer(String assertion, String variableNotFound) {
        this.original = assertion;
        this.variableNotFound = variableNotFound;
    }

    @Override
    public void visit(final SimpleName n, final Void arg) {
        super.visit(n, arg);

        if(n.asString().equals(variableNotFound) && !doneSet.contains(n.asString())){
            String s = new String(this.original);
            while(s.contains(n.asString())){
                s = s.replace(n.asString(), "<insert>");
            }
            
            doneSet.add(variableNotFound);
            addReplacement(s);
        }
    }

    private void addReplacement(String s) {
        if (s.contains("<insert>")) {
            replacements.add(s);
        }
    }
}