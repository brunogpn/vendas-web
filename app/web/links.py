"""Link de checkout de um plano — regra única para todo lugar que manda a cliente pagar.

O plano padrão é o do link sem `?plano=`; os outros levam `plano=<slug>`. Landing, Estante, "Meu acesso" do
app, retomada do checkout e e-mails usam esta função, para nenhum link abrir o plano errado (ex.: um pedido
do Completo reaberto como Básico).
"""
from urllib.parse import urlencode


def link_checkout(produto_id, plano: dict | None = None, *, v2: bool = False, pedido=None, ref=None,
                  oferta=None, musica=None) -> str:
    """'/pay/<id>' (ou '/pay2/<id>') com, nesta ordem, pedido, ref, plano (só se não for o padrão), oferta e
    musica (token da música que o produto Música vende). `plano`: dict com 'slug' e 'padrao' (None = o padrão)."""
    params = []
    if pedido:
        params.append(('pedido', pedido))
    if ref:
        params.append(('ref', ref))
    if plano and not plano.get('padrao'):
        params.append(('plano', plano['slug']))
    if oferta:
        params.append(('oferta', oferta))
    if musica:
        params.append(('musica', musica))
    caminho = f"/pay{'2' if v2 else ''}/{int(produto_id)}"
    return caminho + (f'?{urlencode(params)}' if params else '')
