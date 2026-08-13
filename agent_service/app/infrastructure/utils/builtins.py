# ===========================================
# BUILT-IN CLASS/OBJECT NAMES BY LANGUAGE
# ===========================================

PHP_BUILTINS = {
    "Exception", "Error", "Throwable", "ArrayObject", "Closure",
    "DateTime", "DateTimeImmutable", "stdClass", "Traversable",
    "LogicException", "RuntimeException", "PDO", "mysqli", "SplFileInfo",
    "DirectoryIterator", "JsonSerializable", "Generator"
}

PYTHON_BUILTINS = {
    "Exception", "BaseException", "ValueError", "TypeError", "IOError",
    "FileNotFoundError", "OSError", "dict", "list", "tuple", "set", "frozenset",
    "int", "float", "str", "bool", "bytes", "bytearray", "object",
    "enumerate", "zip", "map", "filter", "range", "print", "len", "sum",
    "open", "input", "max", "min", "abs", "round", "isinstance", "type"
}

JAVASCRIPT_BUILTINS = {
    "Error", "EvalError", "RangeError", "ReferenceError", "SyntaxError",
    "TypeError", "URIError", "Array", "Object", "String", "Number", "Boolean",
    "Map", "Set", "WeakMap", "WeakSet", "Date", "RegExp", "Promise", "Function",
    "Symbol", "BigInt", "JSON", "Math", "Reflect", "Proxy", "Intl"
}

C_SHARP_BUILTINS = {
    "Exception", "SystemException", "Object", "String", "Int32", "Double",
    "Boolean", "Char", "Array", "List", "Dictionary", "Queue", "Stack",
    "DateTime", "TimeSpan", "Guid", "Math", "Console", "File", "Stream",
    "Task", "Tuple", "ValueTuple", "Action", "Func"
}

CPP_BUILTINS = {
    "std::string", "std::vector", "std::map", "std::set", "std::queue",
    "std::stack", "std::list", "std::pair", "std::tuple", "std::exception",
    "std::runtime_error", "std::logic_error", "std::out_of_range", "std::unique_ptr",
    "std::shared_ptr", "std::weak_ptr", "std::optional", "std::variant", "std::thread",
    "std::mutex", "std::atomic", "std::chrono", "std::filesystem"
}

TYPESCRIPT_BUILTINS = JAVASCRIPT_BUILTINS.union({
    "ReadonlyArray", "Record", "Partial", "Required", "Pick", "Omit", "Exclude",
    "Extract", "NonNullable", "Parameters", "ReturnType", "InstanceType"
})

GO_BUILTINS = {
    "error", "bool", "string", "int", "int8", "int16", "int32", "int64",
    "uint", "uint8", "uint16", "uint32", "uint64", "float32", "float64",
    "complex64", "complex128", "byte", "rune", "map", "chan", "interface",
    "append", "copy", "delete", "len", "cap", "close", "panic", "recover",
    "make", "new", "print", "println"
}

RUBY_BUILTINS = {
    "Exception", "StandardError", "RuntimeError", "IOError", "ArgumentError",
    "TypeError", "Array", "Hash", "String", "Integer", "Float", "Symbol",
    "Range", "Time", "Dir", "File", "Regexp", "Enumerator", "Proc", "Thread",
    "IO", "Object", "Kernel", "NilClass", "TrueClass", "FalseClass"
}

# 🟢 New Dart built-ins
DART_BUILTINS = {
    # Core types
    "Object", "Null", "bool", "num", "int", "double", "String", "Symbol",
    "List", "Map", "Set", "Iterable", "Iterator",

    # Core classes
    "DateTime", "Duration", "Uri", "RegExp", "Runes", "BigInt", "Comparator",
    "Pattern", "StackTrace", "TypeError", "UnimplementedError", "StateError",
    "ArgumentError", "RangeError", "FormatException", "Future", "Stream",

    # Collections and utilities
    "LinkedHashMap", "LinkedHashSet", "HashMap", "HashSet", "Queue", "IterableMixin",

    # Async and IO
    "Timer", "StreamController", "StreamSink", "Sink",

    # Misc
    "print", "identical", "assert", "Comparable"
}

JAVA_BUILTINS = {
    # Core
    "Object", "Class", "String", "System", "Thread", "Runnable", "Math",
    "Integer", "Double", "Float", "Long", "Short", "Byte", "Boolean", "Character",

    # Exceptions & Errors
    "Exception", "RuntimeException", "Error", "Throwable",
    "IOException", "FileNotFoundException", "NullPointerException",
    "IllegalArgumentException", "IndexOutOfBoundsException",

    # Collections
    "List", "Map", "Set", "HashMap", "TreeMap", "ArrayList",
    "LinkedList", "HashSet", "TreeSet", "Iterator", "Collection",

    # IO & Files
    "File", "InputStream", "OutputStream", "BufferedReader", "BufferedWriter",
    "PrintWriter", "Scanner",

    # Utility & Misc
    "Arrays", "Objects", "Optional", "Locale", "Date", "Calendar",
    "TimeZone", "UUID", "Stream", "Collectors"
}

DEFAULT_BUILTINS = {
    "Exception", "Error", "Object", "String", "Array", "Map", "List",
    "Set", "Dict", "Queue", "Stack", "File", "Math", "DateTime", "Thread",
    "Function", "Class", "System"
}




def get_builtins_for_language(lang: str):
    lang = lang.lower()
    mapping = {
        "php": PHP_BUILTINS,
        "python": PYTHON_BUILTINS,
        "javascript": JAVASCRIPT_BUILTINS,
        "typescript": TYPESCRIPT_BUILTINS,
        "java": JAVA_BUILTINS,
        "dart": DART_BUILTINS,
        "csharp": C_SHARP_BUILTINS,
        "cpp": CPP_BUILTINS,
        "go": GO_BUILTINS,
        "ruby": RUBY_BUILTINS
    }
    return mapping.get(lang, DEFAULT_BUILTINS)

