package ncsusoftware;

import org.junit.Assert;
import org.junit.Test;

/**
 * Unit test for simple App.
 */
public class AnotherTest {

    String somefield;

    public int someHelper() { return 0; }

    /**
     * Create the test case
     *
     * @param testName name of the test case
     */
    public AnotherTest( String testName) {    }

    
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
}
