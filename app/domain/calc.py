def calcular_subtotal(precio, cantidad):
    return round(float(precio) * int(cantidad), 2)

def calcular_total(items):
    return round(sum(float(item["subtotal"]) for item in items), 2)
