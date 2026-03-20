import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from "recharts";

export default function WeeklyChart({ data }) {
  if (!data || data.length === 0) return <div style={{ color: "#AEAEA8", padding: 20, textAlign: "center" }}>Sem dados</div>;

  return (
    <div>
      <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 12, color: "#8A8A85" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "#1A1A18", display: "inline-block" }} /> Score 60+
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "#DCDCD6", display: "inline-block" }} /> Abaixo de 60
        </span>
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} barGap={2}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F0F0EC" vertical={false} />
          <XAxis dataKey="week" tick={{ fontSize: 12, fill: "#AEAEA8" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 12, fill: "#AEAEA8" }} axisLine={false} tickLine={false} width={30} />
          <Bar dataKey="score60" fill="#1A1A18" radius={[4, 4, 0, 0]} barSize={20} name="Score 60+" />
          <Bar dataKey="abaixo" fill="#DCDCD6" radius={[4, 4, 0, 0]} barSize={20} name="Abaixo" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
