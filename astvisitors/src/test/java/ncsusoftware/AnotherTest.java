package ncsusoftware;

import org.junit.Assert;
import org.junit.Test;

import java.util.List;
import java.util.ArrayList;

import info.debatty.java.stringsimilarity.*;

/**
 * Unit test for simple App.
 */
public class AnotherTest {

    String somefield;
    FooClass globalFoo;

    public AnotherTest () { }

    @org.junit.Before
    public void setup() {
        globalFoo = new FooClass();
    }

    public int someHelper() { return 0; }

    /**
     * Create the test case
     *
     * @param testName name of the test case
     */
    // public AnotherTest( String testName) {    }

    
    @Test
    public void testOther()
    {
        int w = 98;
        Assert.assertTrue( true );
    }

    @org.junit.Test
    public void testApp()
    {
        /** local variables **/
        int x = 98;
        String y = "Hello World";
        Object z = new Object();
        Assert.assertTrue( true );
    }

    @org.junit.Test
    public void testAbstraction()
    {
        // Works for Application classes
        FooClass foo = new FooClass();
        foo.sqr(foo.add(5, 3));
        (new FooClass()).add(foo.sqr(3), (float)foo.sqr(4));

        // Works for global fields
        globalFoo.sqr(globalFoo.add(2, 3));

        // Works for Java standard library packages
        List<String> list = new ArrayList<>();
        list.add("A");
        list.size();
        list.get(0);
        list.remove("A");
        list.size();

        // Works for third-party dependencies
        Levenshtein l = new Levenshtein();
        l.distance("String", "String");

        // For factory pattern instantiations, we will still pick-up FooClass as ClassOrInterfaceType but getting constructors might be tricky
        FooClass factoryObj = FooClass.create();
        factoryObj.add(2);

        // Works for dynamic polymorphism as well
        FooSubClass subFoo = new FooSubClass();
        subFoo.add(subFoo.add(3), subFoo.add(4), subFoo.add(5));
    }
}
