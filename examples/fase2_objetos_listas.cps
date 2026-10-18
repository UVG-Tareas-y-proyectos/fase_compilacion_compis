class Cuenta {
    let saldo: integer = 0;
    function constructor(inicial: integer) { this.saldo = inicial; }
    function sumar(monto: integer) { this.saldo = this.saldo + monto; }
    function consultar(): integer { return this.saldo; }
}
class CuentaEspecial: Cuenta {
    let bono: integer = 5;
    function conBono(): integer { return this.consultar() + this.bono; }
}
let cuenta = new CuentaEspecial(10);
let movimientos: integer[] = [2, 3, 4];
movimientos[1] = 8;
foreach (monto in movimientos) { cuenta.sumar(monto); }
print(cuenta.consultar());
print(cuenta.conBono());
