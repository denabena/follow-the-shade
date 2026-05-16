import { redirect } from "next/navigation";

export default function SettingsPage() {
  redirect("/?prefs=1");
}
