public class CalculatorTest {
    public static void main(String[] args) {
        if (Calculator.add(2, 3).value() != 5) {
            throw new AssertionError("add failed");
        }
        System.out.println("2 tests passed");
    }
}
