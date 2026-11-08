// Cada llamada conserva su propio marco en la pila MIPS.
function factorial(n: integer): integer {
    if (n <= 1) { return 1; }
    return n * factorial(n - 1);
}
function sumar(a: integer, b: integer, c: integer, d: integer, e: integer): integer {
    return a + b + c + d + e;
}
let conservado: integer = 25;
print(factorial(6));
print(sumar(1, 2, 3, 4, 5));
print(conservado);
