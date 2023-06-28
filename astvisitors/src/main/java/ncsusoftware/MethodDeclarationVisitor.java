package ncsusoftware;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.body.MethodDeclaration;

public class MethodDeclarationVisitor extends VoidVisitorAdapter<Void> {
    List<String[]> methods = new ArrayList<String[]>();

    MethodDeclarationVisitor() {
    }

    @Override
    public void visit(final MethodDeclaration n, final Void arg) {
        super.visit(n, arg);

        String[] methodDetails = { n.getName().toString(), String.valueOf(n.getBegin().get().line), String.valueOf(n.getEnd().get().line)};
        methods.add(methodDetails);
    }

    public static List<String> listFiles(String root){
        if (!Files.isDirectory(Paths.get(root))) {
            throw new IllegalArgumentException("Path must be a directory!");
        }

        List<String> result = null;
        try (Stream<Path> walk = Files.walk(Paths.get(root))) {
            result = walk
                    .filter(Files::isRegularFile)   // is a file
                    .filter(p -> p.getFileName().toString().endsWith(".java"))
                    .map(p -> p.toString())
                    .collect(Collectors.toList());
        }catch(Exception e){
            System.out.println("File listing EXCEPTION: " + e.toString());
        }

        return result;
    }
}