function contador(inicio: integer): Closure {
    function siguiente(): integer {
        inicio = inicio + 1;
        return inicio;
    }
    return siguiente;
}
let primero = contador(10);
let segundo = contador(20);
print(primero());
print(primero());
print(segundo());
class Cuenta {
    let saldo: integer = 10;
    function agregar(monto: integer) { this.saldo = this.saldo + monto; }
    function consultar(): integer { return this.saldo; }
}
class CuentaConBono: Cuenta {
    let bono: integer = 5;
    function consultar(): integer { return this.saldo + this.bono; }
}
let cuenta = new CuentaConBono();
let montos: integer[] = [2, 3, 4];
foreach (monto in montos) { cuenta.agregar(monto); }
print(cuenta.consultar());
