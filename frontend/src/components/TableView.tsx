interface Props {
  columns: [string, string];
  rows: [string | number, number][];
}

export default function TableView({ columns, rows }: Props) {
  return (
    <details>
      <summary>Table view</summary>
      <table>
        <thead>
          <tr>
            <th>{columns[0]}</th>
            <th>{columns[1]}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
