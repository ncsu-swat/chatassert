package ncsusoftware;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;

import java.util.Optional;
import java.util.Scanner;
import java.io.File;
import java.io.FileWriter;
import java.io.FileNotFoundException;
import java.io.IOException;

public class PY4JGateway{
    String filePath;
    private JavaParser jParser;
    private CompilationUnit cu;

    PY4JGateway(){

    }

    PY4JGateway(String filePath) throws FileNotFoundException{
        setFile(filePath);
    }

    public int setFile(String filePath) throws FileNotFoundException{
        this.filePath = filePath;
        String content = new Scanner(new File(this.filePath)).useDelimiter("\\Z").next();

        this.jParser = new JavaParser();
        this.cu = ParseUtil.parseCompilationUnit(jParser, content);

        return 0;
    }

    public int inject(String methodName, String newMethod){
        MethodDeclaration newMD = null;
        try{
            System.out.println("\n\nInjecting: " + methodName);

            newMD = ParseUtil.parseMethodDeclaration(this.jParser, newMethod);
            MethodInjectorTransformer mi = new MethodInjectorTransformer(methodName, newMD);

            mi.visit(this.cu, null);
            rewriteFile(this.cu);
        }catch(RuntimeException e){
            System.out.println("Exception has occurred - {}".format(e.toString()));
            return -1;
        }

        return 0;
    }

    public int rewriteFile(CompilationUnit cu){
        FileWriter writer = null;
        try{
            writer = new FileWriter(this.filePath);
            writer.write(cu.toString());
            writer.close();
        }catch(IOException e){
            System.out.println("Exception occurred - " + e.toString());
        }

        return 0;
    }

    public String prefixHoleForMethodNotFound(String assertion, String methodNotFound){
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(assertion).getResult();
        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
            // ParseUtil.printTypesContentsRecursively(stmt);

            PrefixInjectionTransformer holeInjector = new PrefixInjectionTransformer(stmt.toString(), methodNotFound);
            stmt.accept(holeInjector, null);

            if(holeInjector.replacements.size() > 0){
                return holeInjector.replacements.get(0);
            }else{
                return assertion;
            }
        } else {
            return assertion;
        }
    }

    public List<String> findHoleFillers(String testMethodName){
        IdFinderVisitor visitor = new IdFinderVisitor(testMethodName);
        this.cu.accept(visitor, null);

        return visitor.allFillers;
    }
}

