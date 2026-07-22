import type { ReactNode } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@xray/ui/components/alert-dialog";
import { cn } from "@xray/ui/lib/utils";
import { buttonVariants } from "@xray/ui/components/button";

interface Props {
  title: string;
  description?: string;
  onConfirm: () => void;
  confirmText?: string;
  cancelText?: string;
  destructive?: boolean;
  children: ReactNode;
}

export default function ConfirmButton({
  title,
  description,
  onConfirm,
  confirmText = "Confirm",
  cancelText = "Cancel",
  destructive,
  children,
}: Props) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelText}</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={destructive ? cn(buttonVariants({ variant: "destructive" })) : undefined}
          >
            {confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
