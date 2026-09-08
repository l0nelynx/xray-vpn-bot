import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { ArrowLeft, Send } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { Textarea } from "@xray/ui/components/textarea";
import { SupportImages } from "@xray/ui/components/support-images";
import { Dialog, DialogContent, DialogTitle } from "@xray/ui/components/dialog";
import { useSupportPolling } from "@xray/ui/hooks/useSupportPolling";
import { useSupportDraft } from "@xray/ui/hooks/useSupportDraft";
import { api, support, AttachmentOut, TicketDetail } from "../api/client";
import { useAuthedImage } from "../hooks/useAuthedImage";
import { useT } from "../i18n/LocaleContext";

function Photo({ item, open }: { item: AttachmentOut; open: (url: string)=>void }) { const url=useAuthedImage(item.url); return url ? <button onClick={()=>open(url)} aria-label={item.filename}><img src={url} alt={item.filename} className="w-24 h-24 object-cover rounded-lg"/></button> : <span className="text-xs">…</span>; }
export default function SupportTicketPage() { const { id }=useParams(); return <Conversation key={id} id={Number(id)}/>; }
function Conversation({id}:{id:number}) {
 const navigate=useNavigate(); const [params]=useSearchParams(); const {locale,dateLocale}=useT(); const ru=locale==="ru";
 const {data:ticket,error,reload}=useSupportPolling<TicketDetail>(String(id),()=>api.get(`/support/tickets/${id}`));
 const [reply,setReply]=useSupportDraft(`miniapp:${id}`); const [files,setFiles]=useState<File[]>([]); const [busy,setBusy]=useState(false); const [sendError,setSendError]=useState<string|null>(null); const [preview,setPreview]=useState<string|null>(null); const [hasNew,setHasNew]=useState(false);
 const scroll=useRef<HTMLDivElement>(null); const bottom=useRef(true); const read=useRef(0);
 const labels:Record<string,string>=ru?{open:"Ждём ответа поддержки",in_progress:"Проверяем вашу проблему",waiting_user:"Поддержка ответила · ждём вас",closed:"Обращение закрыто"}:{open:"Waiting for support",in_progress:"Investigating your issue",waiting_user:"Support replied · your turn",closed:"Request closed"};
 const markRead=()=>{const cursor=ticket?.last_message_id||0;if(cursor<=read.current||document.hidden)return;read.current=cursor;void api.post(`/support/tickets/${id}/read`,{message_id:cursor}).then(()=>window.dispatchEvent(new Event("support-read"))).catch(()=>{read.current=0;});};
 useEffect(()=>{if(!ticket)return;if(bottom.current){scroll.current?.scrollTo({top:scroll.current.scrollHeight});markRead();}else setHasNew(true);},[ticket?.messages.length,ticket?.last_message_id]);
 const jump=()=>{bottom.current=true;scroll.current?.scrollTo({top:scroll.current.scrollHeight,behavior:"smooth"});setHasNew(false);markRead();};
 const send=async()=>{if(busy||(!reply.trim()&&!files.length))return;setBusy(true);setSendError(null);try{await support.addMessage(id,reply.trim(),files);setReply("");setFiles([]);bottom.current=true;await reload();}catch(e){setSendError((e as Error).message);}finally{setBusy(false);}};
 const outcome=async(action:string)=>{if(busy)return;setBusy(true);setSendError(null);try{await api.post(`/support/tickets/${id}/outcome`,{action});await reload();}catch(e){setSendError((e as Error).message);}finally{setBusy(false);}};
 return <div className="mini-support-chat">
  <header className="mini-support-header"><Button variant="ghost" size="sm" onClick={()=>navigate("/support")}><ArrowLeft size={16}/>{ru?"Обращения":"Requests"}</Button>{ticket&&<><div className="text-xs text-muted-foreground mt-2">#{id}</div><h1 className="text-lg font-semibold break-words">{ticket.subject}</h1><div className="text-xs text-muted-foreground mt-1">{labels[ticket.status]}</div></>}</header>
  {params.has("created")&&<p className="px-4 py-2 text-xs text-muted-foreground">{ru?"Обращение принято. Ответ появится здесь; уведомление придёт в Telegram, если бот доступен.":"Request received. The reply will appear here; Telegram will notify you if the bot is available."}</p>}
  {error&&<div role="alert" className="px-4 text-sm text-destructive">{ru?"Не удалось обновить переписку.":"Could not refresh messages."}<Button size="sm" variant="ghost" onClick={()=>void reload()}>{ru?"Повторить":"Retry"}</Button></div>}
  <div className="mini-support-messages" ref={scroll} onScroll={()=>{const el=scroll.current!;bottom.current=el.scrollHeight-el.scrollTop-el.clientHeight<60;if(bottom.current){setHasNew(false);markRead();}}}>
   {!ticket&&!error&&<p className="text-sm text-muted-foreground">{ru?"Загружаем переписку…":"Loading messages…"}</p>}
   {ticket?.messages.map(m=><article key={m.id} className={`mini-support-bubble ${m.sender}`}><p className="whitespace-pre-wrap break-words text-sm">{m.text}</p><div className="flex flex-wrap gap-2 mt-2">{m.attachments?.map(a=><Photo key={a.id} item={a} open={setPreview}/>)}</div><div className="text-[11px] opacity-60 mt-2">{m.sender==="admin"?(ru?"Поддержка":"Support"):(ru?"Вы":"You")} · {new Date(m.created_at).toLocaleString(dateLocale,{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"})}</div></article>)}
  </div>
  {hasNew&&<Button size="sm" variant="secondary" className="mx-auto" onClick={jump}>{ru?"Новые сообщения ↓":"New messages ↓"}</Button>}
  {ticket&&<footer className="mini-support-composer">
    {sendError&&<p role="alert" className="text-sm text-destructive mb-2">{sendError}</p>}
    {(ticket.status==="waiting_user"||ticket.status==="closed")&&<div className="flex flex-wrap gap-2 mb-3">{ticket.status!=="closed"&&<Button variant="outline" size="sm" disabled={busy} onClick={()=>void outcome("resolved")}>{ru?"Помогло, спасибо":"Solved, thank you"}</Button>}{(ticket.status!=="closed"||ticket.can_reopen)&&<Button variant="outline" size="sm" disabled={busy} onClick={()=>void outcome("reopen")}>{ru?"Проблема осталась":"Still need help"}</Button>}</div>}
    {ticket.status==="closed"?<div className="text-sm text-muted-foreground">{ticket.can_reopen?(ru?"Можно вернуться к этой переписке в течение 7 дней после закрытия.":"You can reopen this conversation within 7 days of closing."):<Button variant="outline" onClick={()=>navigate("/support/new")}>{ru?"Создать новое обращение":"Create a new request"}</Button>}</div>:<>
     <Textarea aria-label={ru?"Ваше сообщение":"Your message"} placeholder={ru?"Ваше сообщение…":"Your message…"} rows={2} maxLength={4000} disabled={busy} value={reply} onChange={e=>setReply(e.target.value)}/>
     <div className="flex justify-between text-[11px] text-muted-foreground my-2"><span>{reply?(ru?"Черновик сохранён":"Draft saved"):""}</span><span>{reply.length}/4000</span></div>
     <div className="flex items-end justify-between gap-2"><SupportImages files={files} onChange={setFiles} onError={setSendError} label={ru?"Фото":"Photo"} disabled={busy}/><Button aria-label={ru?"Отправить":"Send"} disabled={busy||(!reply.trim()&&!files.length)} onClick={()=>void send()}><Send size={18}/>{busy?"…":""}</Button></div>
    </>}
  </footer>}
  <Dialog open={!!preview} onOpenChange={(open: boolean)=>!open&&setPreview(null)}><DialogContent className="max-w-[90vw]"><DialogTitle className="sr-only">{ru?"Фото":"Photo"}</DialogTitle>{preview&&<img src={preview} alt={ru?"Вложение":"Attachment"} className="max-h-[80dvh] object-contain"/>}</DialogContent></Dialog>
 </div>;
}
