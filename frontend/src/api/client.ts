import type { ChatMessage, DogProfile, Fault, Me, Rating } from "./types"

export type HvostunApi = {
  login(login: string, password: string, consent: boolean): Promise<void>
  logout(): Promise<void>
  me(): Promise<Me | null>
  getProfile(): Promise<DogProfile>
  saveDraft(profile: DogProfile): Promise<Me>
  saveProfile(profile: DogProfile): Promise<Me>
  startSurvey(): Promise<Me>
  saveAnswer(value: number): Promise<Me>
  finishSurvey(): Promise<Me>
  listMessages(): Promise<ChatMessage[]>
  sendMessage(text: string): Promise<ChatMessage[]>
  deleteMessage(id: string): Promise<ChatMessage[]>
  setFeedback(id: string, rating: Rating, comment?: string): Promise<void>
  track(name: string, screen: string, payload?: unknown): Promise<void>
  setFault?(fault: Fault): void
}
