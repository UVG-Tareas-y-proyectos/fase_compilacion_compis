class Animal {
    let nombre: string;

    function constructor(nombre: string) {
        this.nombre = nombre;
    }

    function hablar(): string {
        return this.nombre + " hace ruido";
    }
}

class Perro : Animal {
    function hablar(): string {
        return this.nombre + " ladra";
    }
}

function crearContador(inicio: integer): integer {
    let paso: integer = 1;
    function siguiente(): integer {
        return inicio + paso;
    }
    return siguiente();
}

let mascota: Perro = new Perro("Toby");
let notas: integer[] = [90, 85, 100];
let primera: integer = notas[0];
print(mascota.hablar());
print(crearContador(10));
print(primera);

