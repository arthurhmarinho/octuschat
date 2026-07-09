export const metadata = {
  title: "Política de Privacidade — Octus Chat",
};

export default function PrivacidadePage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16 text-sm leading-relaxed text-[var(--fg)]">
      <h1 className="mb-2 text-2xl font-bold">Política de Privacidade — Octus Chat</h1>
      <p className="mb-8 text-[var(--muted)]">Última atualização: 30/06/2026</p>

      <div className="space-y-5">
        <p>
          O Octus Chat conecta contas profissionais do Instagram para automatizar
          respostas (DMs) a comentários e mensagens. Esta política explica quais dados
          tratamos e como.
        </p>

        <section>
          <h2 className="mb-1 font-semibold">Dados que coletamos</h2>
          <p className="text-[var(--muted)]">
            Ao conectar sua conta via Meta, armazenamos: o identificador da conta, o
            nome de usuário, o token de acesso (para operar em seu nome) e os dados de
            interações necessárias à automação (comentários, mensagens enviadas e
            recebidas, e contatos que interagiram).
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold">Como usamos</h2>
          <p className="text-[var(--muted)]">
            Usamos esses dados exclusivamente para executar as automações que você
            configura (enviar DMs, listar conversas e contatos). Não vendemos nem
            compartilhamos seus dados com terceiros para fins de marketing.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold">Retenção e exclusão</h2>
          <p className="text-[var(--muted)]">
            Você pode desconectar sua conta e solicitar a exclusão dos seus dados a
            qualquer momento — veja a página{" "}
            <a href="/exclusao-de-dados" className="text-[var(--gold)] underline">
              Exclusão de Dados
            </a>
            . Ao desconectar, o token de acesso é revogado e os dados associados são
            removidos.
          </p>
        </section>

        <section>
          <h2 className="mb-1 font-semibold">Contato</h2>
          <p className="text-[var(--muted)]">
            Dúvidas sobre privacidade: entre em contato pelo e-mail do responsável pelo
            app.
          </p>
        </section>
      </div>
    </main>
  );
}
