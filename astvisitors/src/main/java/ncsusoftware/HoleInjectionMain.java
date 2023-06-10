package ncsusoftware;

import com.github.javaparser.JavaParser;

import java.util.Collections;
import java.util.Comparator;
import java.util.Optional;
import java.io.FileNotFoundException;

public class HoleInjectionMain {

    public static void main(String[] args) throws FileNotFoundException {
        // test cases... :-/
        // String s =  "Assert.assertEquals(head.getHead(), Label.of(\"hula\"));";
        // String s = "Assert.assertEquals(method, \"testLocalTeardownFilter\");";
        // String s = "Assert.assertEquals(OBJECT, byteSerializer.deserializeNative(buffer));";
        // String s = "Assert.assertEquals(\"Turpm\u0101kaj\u0101\", Turpm\u0101kaj\u0101.getLemma());";
        // String s = "Assert.assertEquals(null, HazelcastStarter.getHazelcastVersionFromJarOrNull(file));";
        // String s = "Assert.assertEquals(1, a(w,t));";        
        // String s = "Assert.assertEquals(\"a\", this.y.z(w, tmp));";     
        // String s = "Assert.assertEquals(false || x(), this.y.z(w));";
        // String s = "Assert.assertEquals(1.0, this.y.z(w));";        
        // String s = "Assert.assertEquals(x+1, this.y.z(w));";
        // String s = "Assert.assertEquals(x+1, this.y.z());";
        // String s = "Assert.assertEquals(x+1, this.y.z);";
        // String s = "Assert.assertEquals(y, this.y.z);";
        // String s = "Assert.assertEquals(x+1, a.b());";
        holeInjection(args[0]);
    }

    private static void holeInjection(String s) {
        
        JavaParser jparser = new JavaParser();
        Optional<com.github.javaparser.ast.stmt.Statement> optStmt = jparser.parseStatement(s).getResult();
        if (optStmt.isPresent()) {
            com.github.javaparser.ast.stmt.Statement stmt = optStmt.get();
            // for debugging:
            // ParseUtil.printTypesContentsRecursively(stmt);

            HoleInjectionTransformer holeInjector = new HoleInjectionTransformer(stmt.toString());
            stmt.accept(holeInjector, null);
            /** sort the list of candidates */
            Comparator<String> comp = new Comparator<String>() {
                @Override
                public int compare(String o1, String o2) {
                    int x = o1.length();
                    int y = o2.length();
                    return  (x > y) ? 1: (x < y) ? -1: 0;
                }
            };
            Collections.sort(holeInjector.replacements, comp);
            /** print the list of candidates */
            for (String candidate : holeInjector.replacements) {
                /** hacks! discard special cases */                
                if (candidate.equals("<insert>;")) continue;
                if (candidate.contains("<insert>.")) continue;
                if (candidate.contains("\"<insert>\"")) continue;
                System.out.println(candidate);
            }

        }
    }

}