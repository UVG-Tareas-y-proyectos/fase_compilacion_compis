let total: integer = 0;
for (let i: integer = 0; i < 5; i = i + 1) {
    if (i == 2) { continue; }
    total = total + i;
}
while (total < 10) { total = total + 1; }
do { total = total - 1; } while (total > 8);
switch (total == 8) {
    case true: print("total correcto"); break;
    default: print("revisar");
}
print(total);
