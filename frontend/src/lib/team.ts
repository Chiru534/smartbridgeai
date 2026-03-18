export type TeamMember = {
    id: string;
    name: string;
    username: string;
    role: string;
    initials: string;
    color: string;
    department: string;
};

export const TEAM_MEMBERS: TeamMember[] = [
    { id: "0", name: "Admin", username: "admin", role: "Administrator", initials: "AD", color: "bg-indigo-500", department: "Management" },
    { id: "1", name: "Ravi Sharma", username: "ravi", role: "Full Stack Developer", initials: "RS", color: "bg-blue-400", department: "Engineering" },
    { id: "2", name: "Ananya Patel", username: "ananya", role: "UI/UX Designer", initials: "AP", color: "bg-emerald-400", department: "Design" },
    { id: "3", name: "Kiran Desai", username: "kiran", role: "Backend Engineer", initials: "KD", color: "bg-amber-400", department: "Engineering" },
    { id: "4", name: "Priya Raj", username: "priya", role: "Project Manager", initials: "PR", color: "bg-rose-400", department: "Management" },
    { id: "5", name: "Amit Verma", username: "amit", role: "Data Scientist", initials: "AV", color: "bg-violet-400", department: "Data" },
    { id: "6", name: "Employee", username: "employee", role: "Team Member", initials: "EM", color: "bg-slate-400", department: "Engineering" },
];

export function getMemberByName(name: string): TeamMember | undefined {
    return TEAM_MEMBERS.find(m => m.name.toLowerCase() === name.toLowerCase());
}

export function getMemberByUsername(username: string): TeamMember | undefined {
    return TEAM_MEMBERS.find(m => m.username.toLowerCase() === username.toLowerCase());
}

export function getMemberColor(nameOrUsername: string): string {
    const member = getMemberByUsername(nameOrUsername) || getMemberByName(nameOrUsername);
    return member?.color ?? "bg-slate-400";
}

export function getMemberInitials(nameOrUsername: string): string {
    const member = getMemberByUsername(nameOrUsername) || getMemberByName(nameOrUsername);
    if (member) return member.initials;
    return nameOrUsername.substring(0, 2).toUpperCase();
}
