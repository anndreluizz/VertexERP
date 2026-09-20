"""Catalogo fixo de permissoes que um Perfil pode conceder -- so' cobre
acoes hoje travadas em admin (ver grep por get_current_admin nos
routers) que fazem sentido delegar pra um usuario de confianca sem
promove-lo a admin de verdade. Gerenciar usuarios/perfis, criar loja e
editar configuracoes da loja continuam admin-only sempre (nunca entram
aqui), pra nao abrir brecha de um perfil se auto-conceder mais poder."""

PERMISSOES_DISPONIVEIS = {
    "produtos.excluir": "Excluir produtos",
    "categorias.excluir": "Excluir categorias de produto",
    "marcas.excluir": "Excluir marcas",
    "fornecedores.excluir": "Excluir fornecedores",
    "categorias_despesa.excluir": "Excluir categorias de despesa",
    "centros_custo.excluir": "Excluir centros de custo",
    "plano_contas.excluir": "Excluir contas do plano de contas",
    "compras.cancelar": "Cancelar compras",
    "vendas.cancelar": "Cancelar vendas",
    "contas_receber.cancelar": "Cancelar contas a receber",
    "caixa.fechar": "Fechar caixa",
    "aprovacoes.gerenciar": "Aprovar/rejeitar solicitações",
    "clientes.lgpd": "Exportar/apagar dados de cliente (LGPD)",
}
