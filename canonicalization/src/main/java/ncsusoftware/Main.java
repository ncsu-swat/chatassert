package ncsusoftware;

import com.github.javaparser.JavaParser;


import java.util.Optional;

public class Main {
    public static void main(String[] args) throws Exception {
        String s = "Assert.assertEquals(y, this.y.z);";
        //TODO: it crashes on this case! try generalizing to demonstrate you understood the infrastructure. -Marcelo
        // String s = "Assert.assertEquals(this.y, this.y.z);";
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(s).getResult();
        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
            // for debugging:
            // ParseUtil.printTypesContentsRecursively(stmt);
            ThisTransformer methodCounter = new ThisTransformer();
            methodCounter.visitStmt(stmt);

            System.out.println(stmt);
        }        
    }

}