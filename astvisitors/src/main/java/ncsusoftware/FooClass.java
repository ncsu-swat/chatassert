package ncsusoftware;

public class FooClass {
    public static FooClass create(){
        return new FooClass();
    }

    public int add(int a, float b){
        return a+(int)b;
    }

    public int add(int a){
        return a + a;
    }

    public int sqr(int c){
        return c*c;
    }
}