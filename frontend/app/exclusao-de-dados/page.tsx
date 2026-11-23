export const metadata = {
  title: "Exclusão de Dados — Octus Chat",
};

export default function ExclusaoDeDadosPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16 text-[15px] leading-6 text-fg-2">
      <h1 className="mb-2 text-[28px] font-medium leading-9 text-fg">Exclusão de Dados — Octus Chat</h1>
      <p className="mb-8 text-fg-3">Última atualização: 30/06/2026</p>

      <div className="space-y-5">
        <p>
          Você pode solicitar a exclusão de todos os dados associados à sua conta do
          Instagram no Octus Chat a qualquer momento.
        </p>

        <section>
          <h2 className="mb-1 font-medium text-fg">Como solicitar</h2>
          <p>
            Envie um e-mail ao responsável pelo app informando o nome de usuário do
            Instagram conectado. Processamos a exclusão em até 30 dias.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-medium text-fg">O que é removido</h2>
          <p>
            A conta conectada, o token de acesso, as automações, os contatos e o
            histórico de mensagens vinculados a ela são apagados de forma permanente.
          </p>
        </section>
      </div>
    </main>
  );
}
