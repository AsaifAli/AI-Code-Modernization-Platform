<?php
require __DIR__ . '/../Calculator.php';
if (Calculator::add(2, 3) !== 5) {
    throw new RuntimeException('add failed');
}
echo "1 test passed\n";
