package ncsusoftware;

import com.github.javaparser.JavaParser;

import java.util.Collections;
import java.util.Comparator;
import java.util.Optional;
import java.io.FileNotFoundException;

import com.github.javaparser.ParseResult;
import com.github.javaparser.ParseStart;
import com.github.javaparser.StringProvider;
import com.github.javaparser.ast.body.MethodDeclaration;

public class AbstractionMain {

    public static void main(String[] args) throws FileNotFoundException {
        JavaParser jparser = new JavaParser();

        String s = "@Test\n public void testAddWconnithPoolKey_multiPoolKey ( ) throws InterruptedException {\n     Connection conn = getAConn ( ) ; \n     cm . add ( conn , poolKey ) ; \n     cm . add ( conn , \"STR\" ) ; \n     cm . add ( conn , \"STR\" ) ; \n     Assert.assertEquals(1,cm.count(poolKey));\n}";
        Optional<MethodDeclaration> optStmt = jparser.parse(ParseStart.METHOD_DECLARATION, new StringProvider(s)).getResult();

        if (optStmt.isPresent()) {
            MethodDeclaration stmt = optStmt.get();
            // for debugging:
            // ParseUtil.printTypesContentsRecursively(stmt);

            AbstractionVisitor abstractionVisitor = new AbstractionVisitor();
            stmt.accept(abstractionVisitor, null);

            System.out.println(abstractionVisitor.perLine);
        } else {
            System.out.println("------empty------");
        }
    }
}