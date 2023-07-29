package ncsusoftware;

import com.github.javaparser.ast.visitor.VoidVisitorAdapter;

import com.github.javaparser.ast.PackageDeclaration;

public class PackageDeclarationVisitor extends VoidVisitorAdapter<Void> {
    String packageName; 

    PackageDeclarationVisitor() {
        
    }

    @Override
    public void visit(final PackageDeclaration n, final Void arg) {
        super.visit(n, arg);

        this.packageName = n.getName().asString();
        System.out.println("Package name: " + this.packageName);
    }
}