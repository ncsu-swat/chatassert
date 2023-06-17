package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.VariableDeclarator;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.expr.BooleanLiteralExpr;
import com.github.javaparser.ast.expr.DoubleLiteralExpr;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.IntegerLiteralExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.ast.expr.NullLiteralExpr;
import com.github.javaparser.ast.expr.StringLiteralExpr;

public class IdFinderVisitor extends VoidVisitorAdapter<Void> {

    Map<String, String> ids = new HashMap<String, String>();

    IdFinderVisitor() {}

    @Override
    public void visit(final FieldDeclaration n, final Void arg) {
        super.visit(n, arg);
        for (VariableDeclarator vd : n.getVariables()) {
            ids.put(vd.getName().toString(), n.getElementType().asString());
        }
        System.out.println(ids);
    }

    // @Override
    // public void visit(final FieldAccessExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // @Override
    // public void visit(final BinaryExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // @Override
    // public void visit(final MethodCallExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // @Override
    // public void visit(final NameExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // @Override
    // public void visit(final IntegerLiteralExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // @Override
    // public void visit(final DoubleLiteralExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // @Override
    // public void visit(final StringLiteralExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // @Override
    // public void visit(final BooleanLiteralExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // private void addReplacement(String s) {
    //     if (s.contains("<insert>")) {
    //         replacements.add(s);
    //     }
    // }

    // @Override
    // public void visit(final NullLiteralExpr n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }


    // @Override
    // public void visit(final SimpleName n, final Void arg) {
    //     super.visit(n, arg);
    //     String s = replaceFirst(original, n.toString(), "<insert>");
    //     addReplacement(s);
    // }

    // /** Version of replaceFirst that does not use regexes (that can be tricky because of special characters) **/
    // private static String replaceFirst(String source, String target, String replacement) {
    //     int index = source.indexOf(target, /* starting looking after this ==> */source.indexOf("("));
    //     if (index == -1) {
    //         return source;
    //     }    
    //     return source.substring(0, index)
    //         .concat(replacement)
    //         .concat(source.substring(index+target.length()));
    // }
    

}