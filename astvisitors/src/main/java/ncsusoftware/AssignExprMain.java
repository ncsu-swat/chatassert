package ncsusoftware;

import com.github.javaparser.JavaParser;

import java.util.Collections;
import java.util.Comparator;
import java.util.Optional;
import java.io.FileNotFoundException;

public class AssignExprMain {

    public static void main(String[] args) throws FileNotFoundException {
        String s = "a = b.foo();";

        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(s).getResult();

        AssignExprVisitor visitor = new AssignExprVisitor();

        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();

            // for debugging:
            // ParseUtil.printTypesContentsRecursively(stmt);

            stmt.accept(visitor, null);

            System.out.println(visitor.lhs2rhs);
        }
    }
}