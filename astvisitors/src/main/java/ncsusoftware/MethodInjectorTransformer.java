package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;

public class MethodInjectorTransformer extends VoidVisitorAdapter<Void> {

    private String name;
    private MethodDeclaration newMethodDeclaration;

    MethodInjectorTransformer(String name, MethodDeclaration newNode) {
        this.name = name;
        this.newMethodDeclaration = newNode;
    }

    @Override
    public void visit(MethodDeclaration md, Void arg) {
        super.visit(md, arg);
        if (md.getNameAsString().equals(name)) {
            // got parent
            ClassOrInterfaceDeclaration ciDeclaration = (ClassOrInterfaceDeclaration) md.getParentNode().get();
            NodeList<BodyDeclaration<?>> members = ciDeclaration.getMembers();
            for (int i = 0; i< members.size(); i++) {
                final BodyDeclaration bd = members.get(i);
                if (bd instanceof MethodDeclaration) {
                    if (((MethodDeclaration) bd).getNameAsString().equals(name)) {
                        // System.out.println("done");
                        ciDeclaration.setMember(i, newMethodDeclaration);
                        return;
                    }
                }
            }
            throw new RuntimeException("the replacement was unsuccessful. Please, check!");
        }
    }



}