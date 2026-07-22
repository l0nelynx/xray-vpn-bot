import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@xray/ui/components/table";
import { api } from "../api/client";
import type { SquadProfile } from "../api/types";
import ConfirmButton from "../components/ConfirmButton";

interface SquadForm {
  name: string;
  squad_id: string;
  external_squad_id: string;
}

const emptyForm: SquadForm = { name: "", squad_id: "", external_squad_id: "" };

export default function SquadProfilesPage() {
  const [squads, setSquads] = useState<SquadProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SquadProfile | null>(null);
  const [form, setForm] = useState<SquadForm>(emptyForm);

  const patchForm = (patch: Partial<SquadForm>) => setForm((f) => ({ ...f, ...patch }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<SquadProfile[]>("/squads");
      setSquads(data);
    } catch {
      toast.error("Failed to load squad profiles");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setModalOpen(true);
  };

  const openEdit = (record: SquadProfile) => {
    setEditing(record);
    setForm({
      name: record.name,
      squad_id: record.squad_id,
      external_squad_id: record.external_squad_id,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.name || !form.squad_id || !form.external_squad_id) {
      toast.error("All fields are required");
      return;
    }
    try {
      if (editing) {
        await api.put(`/squads/${editing.id}`, form);
        toast.success("Squad updated");
      } else {
        await api.post("/squads", form);
        toast.success("Squad created");
      }
      setModalOpen(false);
      await load();
    } catch {
      toast.error("Failed to save");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/squads/${id}`);
      toast.success("Squad deleted");
      await load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Failed to delete");
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-foreground md:text-xl">Squad Profiles</h1>
        <Button variant="outline" onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add Squad
        </Button>
      </div>

      <div className="overflow-auto rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Name</TableHead>
              <TableHead>Squad ID</TableHead>
              <TableHead>External Squad ID</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {squads.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  {loading ? "Loading..." : "No squad profiles"}
                </TableCell>
              </TableRow>
            ) : (
              squads.map((record) => (
                <TableRow key={record.id}>
                  <TableCell>{record.name}</TableCell>
                  <TableCell>{record.squad_id}</TableCell>
                  <TableCell>{record.external_squad_id}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button size="icon" variant="outline" onClick={() => openEdit(record)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <ConfirmButton
                        title="Delete this squad profile?"
                        destructive
                        onConfirm={() => handleDelete(record.id)}
                      >
                        <Button size="icon" variant="destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </ConfirmButton>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Squad Profile" : "New Squad Profile"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Name *</Label>
              <Input
                placeholder="e.g. France Pro"
                value={form.name}
                onChange={(e) => patchForm({ name: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Squad ID *</Label>
              <Input
                placeholder="RemnaWave squad ID"
                value={form.squad_id}
                onChange={(e) => patchForm({ squad_id: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>External Squad ID *</Label>
              <Input
                placeholder="External squad ID"
                value={form.external_squad_id}
                onChange={(e) => patchForm({ external_squad_id: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
