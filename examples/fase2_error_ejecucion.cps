// Compila correctamente. El índice sólo se comprueba durante la ejecución.
let valores: integer[] = [10, 20];
try {
    print(valores[5]);
} catch (error) {
    print(error);
}
print("el programa continua");
