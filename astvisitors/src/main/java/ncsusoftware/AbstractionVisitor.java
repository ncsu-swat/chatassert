package ncsusoftware;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.Map;
import java.util.LinkedHashMap;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import com.github.javaparser.ast.expr.MethodCallExpr;

public class AbstractionVisitor extends VoidVisitorAdapter<Void> {
    Map<String, String> methodsAndClasses = new LinkedHashMap<>();

    AbstractionVisitor() {
    }

    @Override
    public void visit(final MethodCallExpr n, final Void arg) {
        super.visit(n, arg);

        methodsAndClasses.put(n.getName().toString(), "method");
    }

    @Override
    public void visit(final ClassOrInterfaceType n, final Void arg) {
        super.visit(n, arg);

        if(!n.getName().toString().contains("Exception")){
            methodsAndClasses.put(n.getName().toString(), "class");
        }
    }
}