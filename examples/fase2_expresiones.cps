// Precedencia, conversiones, booleanos y reciclaje de temporales.
let a: integer = 2;
let b: integer = 3;
let c: integer = 4;
let resultado: integer = a + b * c;
let decimal: float = resultado;
let activo: boolean = resultado == 14 && decimal > 10.0;
print(resultado);
print(decimal);
print(activo ? "correcto" : "incorrecto");
