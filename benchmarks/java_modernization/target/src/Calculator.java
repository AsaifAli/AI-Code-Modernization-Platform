public final class Calculator {
    private Calculator() {}

    public record Result(int value) {}

    public static Result add(int left, int right) {
        return new Result(left + right);
    }
}
