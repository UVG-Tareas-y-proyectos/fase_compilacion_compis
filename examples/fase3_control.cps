let total: integer = 0;
for (let i = 0; i < 5; i = i + 1) {
    if (i == 2) { continue; }
    total = total + i;
}
print(total);
print(7 / 2);
print(7 / 2.0);
print(false && (1 / 0 > 0));
let datos: integer[] = [10, 20];
try {
    print(datos[5]);
} catch (error) {
    print(error);
}
print("continuamos");
