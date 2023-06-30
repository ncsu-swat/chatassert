// import com.github.javaparser.JavaParser;
// import com.github.javaparser.ast.CompilationUnit;
// import com.github.javaparser.ast.body.MethodDeclaration;
// import com.github.javaparser.ast.expr.StringLiteralExpr;

// import java.util.Optional;
// import java.util.Scanner;
// import java.util.List;
// import java.util.ArrayList;
// import java.util.Map;
// import java.util.HashMap;
// import java.util.Arrays;

// import java.io.File;
// import java.io.FileWriter;
// import java.io.FileNotFoundException;
// import java.io.IOException;

// public class PrefixInjectionMain {

//     public static void main(String[] args) throws FileNotFoundException {
//         JavaParser jparser = new JavaParser();
//         Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(assertion).getResult();
//         if (optStmt.isPresent()) {
//             com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
//             // ParseUtil.printTypesContentsRecursively(stmt);

//             PrefixInjectionTransformer holeInjector = new PrefixInjectionTransformer(stmt.toString(), methodNotFound);
//             stmt.accept(holeInjector, null);

            
//         } else {
//         }
//     }
// }