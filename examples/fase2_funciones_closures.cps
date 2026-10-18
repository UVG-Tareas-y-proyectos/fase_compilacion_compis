function factorial(n: integer): integer {
    if (n <= 1) { return 1; }
    return n * factorial(n - 1);
}

// Closure es una anotación adicional de fase 2 para retornar funciones.
function crearContador(inicio: integer): Closure {
    let valor: integer = inicio;
    function siguiente(): integer {
        valor = valor + 1;
        return valor;
    }
    return siguiente;
}

let contadorA = crearContador(10);
let contadorB = crearContador(20);
print(factorial(5));
print(contadorA());
print(contadorA());
print(contadorB());
