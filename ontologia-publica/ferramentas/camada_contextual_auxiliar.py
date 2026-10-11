"""Barreira de segurança do perfil público: a camada privada não é distribuída."""
PrivateEntityLayer = object


def load_private_entity_layer(root):
    raise ValueError("Camada contextual privada indisponível no recorte público")
