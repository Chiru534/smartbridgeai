export interface TeamMember {
  id: number;
  name: string;
  role: string;
  department: string;
  initials: string;
  color: string;
}

export const TEAM_MEMBERS: TeamMember[] = [
  { id: 1, name: "Admin", role: "Workspace Owner", department: "Management", initials: "AD", color: "bg-blue-500" },
  { id: 2, name: "Employee", role: "Team Member", department: "General", initials: "EM", color: "bg-emerald-500" },
  { id: 3, name: "Ravi Sharma", role: "Senior Developer", department: "Engineering", initials: "RS", color: "bg-indigo-500" },
  { id: 4, name: "Ananya Patel", role: "UI/UX Designer", department: "Design", initials: "AP", color: "bg-fuchsia-500" },
];

export const getMemberColor = (name: string) => {
  const member = TEAM_MEMBERS.find(m => m.name === name);
  return member ? member.color : "bg-slate-500";
};

export const getMemberInitials = (name: string) => {
  const member = TEAM_MEMBERS.find(m => m.name === name);
  if (member) return member.initials;
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
};
