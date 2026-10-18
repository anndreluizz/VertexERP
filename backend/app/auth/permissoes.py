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
    "vendas.devolver": "Registrar devolução/troca de itens vendidos",
    "vendas.alterar_preco": "Vender com preço diferente do cadastro",
    "produtos.editar_preco": "Alterar preço de venda e promoções",
    "estoque.ajustar": "Ajustar estoque manualmente",
    "contas_pagar.excluir": "Excluir contas a pagar",
    "fiado.corrigir": "Corrigir/excluir lançamentos de fiado",
    "caixa.fechar": "Fechar caixa",
    "aprovacoes.gerenciar": "Aprovar/rejeitar solicitações",
    "clientes.lgpd": "Exportar/apagar dados de cliente (LGPD)",
    "bi.ver": "Ver Inteligência de Negócios (faturamento, fiado, contas)",
    # sem ela o usuario e' "Vendedor": ve so' as proprias vendas/caixa
    # e nao abre Contas a Pagar, Relatorios, Conciliacao nem Compras
    "financeiro.ver": "Ver financeiro: faturamento da loja, vendas de todos, contas a pagar, relatórios, conciliação e compras",
}
