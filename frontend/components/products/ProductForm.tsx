"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, ImagePlus, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { api, photoUrl } from "@/lib/api";
import { useMe } from "@/lib/useMe";

const CATEGORIES = [
  "Rice", "Sugar", "Wheat", "Pulses", "Spices", "Oilseeds",
  "Cotton", "Millets", "Tea", "Coffee", "Other",
] as const;
const UNITS = ["MT", "kg", "quintal"] as const;
const PACKAGING = ["Jute", "PP woven", "HDPE", "Bulk", "Other"] as const;
const MAX_PHOTOS = 5;

export function ProductForm() {
  const router = useRouter();
  const { refetch } = useMe();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [name, setName] = useState("");
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("Rice");
  const [variety, setVariety] = useState("");
  const [originState, setOriginState] = useState("");
  const [packaging, setPackaging] = useState<(typeof PACKAGING)[number] | "">("");
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState<(typeof UNITS)[number]>("MT");
  const [moq, setMoq] = useState("");
  const [pricePerUnit, setPricePerUnit] = useState("");
  const [description, setDescription] = useState("");

  // Photos
  const [photos, setPhotos] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePickFiles = () => fileInputRef.current?.click();

  const handleFilesSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    // Reset the input so re-picking the same file re-fires change
    e.target.value = "";
    if (!files.length) return;
    if (photos.length + files.length > MAX_PHOTOS) {
      setPhotoError(`Up to ${MAX_PHOTOS} photos per product`);
      return;
    }
    setPhotoError(null);
    setUploading(true);
    try {
      for (const file of files) {
        const { url } = await api.uploadProductPhoto(file);
        setPhotos((prev) => [...prev, url]);
      }
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const removePhoto = (url: string) => {
    setPhotos((prev) => prev.filter((p) => p !== url));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setPhotoError(null);
    if (!name.trim()) {
      setError("Product name is required");
      return;
    }
    if (photos.length === 0) {
      setPhotoError("Attach at least one product photo before publishing");
      return;
    }
    setSaving(true);
    try {
      await api.createProduct({
        name: name.trim(),
        category,
        variety: variety.trim() || null,
        originState: originState.trim() || null,
        packaging: packaging || null,
        quantity: quantity ? Number(quantity) : null,
        unit,
        moq: moq ? Number(moq) : null,
        pricePerUnit: pricePerUnit ? Number(pricePerUnit) : null,
        description: description.trim() || null,
        photos,
      });
      await refetch();
      router.replace("/dashboard/products");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create product");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <TextField
        label="Product name"
        placeholder="e.g. Premium Basmati Rice"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="f-category" className="field-label">
            <span>Category</span>
          </label>
          <select
            id="f-category"
            className="field"
            value={category}
            onChange={(e) => setCategory(e.target.value as (typeof CATEGORIES)[number])}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <TextField
          label="Variety / grade"
          placeholder="e.g. 1121 Steam, Sona Masoori"
          value={variety}
          onChange={(e) => setVariety(e.target.value)}
          optional
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          label="Origin (state)"
          placeholder="e.g. Punjab, Maharashtra"
          value={originState}
          onChange={(e) => setOriginState(e.target.value)}
          optional
        />
        <div>
          <label htmlFor="f-packaging" className="field-label">
            <span>Packaging</span>
            <span className="field-label-hint">Optional</span>
          </label>
          <select
            id="f-packaging"
            className="field"
            value={packaging}
            onChange={(e) => setPackaging(e.target.value as (typeof PACKAGING)[number] | "")}
          >
            <option value="">Not specified</option>
            {PACKAGING.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <TextField
          label="Available quantity"
          inputMode="decimal"
          placeholder="0"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value.replace(/[^\d.]/g, ""))}
          optional
        />
        <div>
          <label htmlFor="f-unit" className="field-label">
            <span>Unit</span>
          </label>
          <select
            id="f-unit"
            className="field"
            value={unit}
            onChange={(e) => setUnit(e.target.value as (typeof UNITS)[number])}
          >
            {UNITS.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </div>
        <TextField
          label="Minimum order"
          inputMode="decimal"
          placeholder="0"
          value={moq}
          onChange={(e) => setMoq(e.target.value.replace(/[^\d.]/g, ""))}
          optional
        />
      </div>

      <TextField
        label={`Price per ${unit} (INR)`}
        inputMode="decimal"
        placeholder="Leave blank to invite offers"
        value={pricePerUnit}
        onChange={(e) => setPricePerUnit(e.target.value.replace(/[^\d.]/g, ""))}
        optional
      />

      <div>
        <label htmlFor="f-description" className="field-label">
          <span>Short description</span>
          <span className="field-label-hint">Optional</span>
        </label>
        <textarea
          id="f-description"
          className="field min-h-[96px] py-3"
          placeholder="Notes on quality, sourcing, certifications, availability window…"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      {/* Photos — required */}
      <div>
        <label className="field-label">
          <span>Product photos</span>
          <span className="text-[10px] uppercase tracking-widest text-danger">
            Required
          </span>
        </label>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {photos.map((rel) => (
            <div
              key={rel}
              className="group relative aspect-square overflow-hidden rounded-lg border border-line bg-ink-elevated"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={photoUrl(rel)}
                alt="Product"
                className="h-full w-full object-cover"
              />
              <button
                type="button"
                onClick={() => removePhoto(rel)}
                aria-label="Remove photo"
                className="absolute right-1.5 top-1.5 inline-flex h-6 w-6 items-center justify-center rounded-full bg-ink/80 text-paper opacity-0 backdrop-blur-sm transition-opacity group-hover:opacity-100"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}

          {photos.length < MAX_PHOTOS ? (
            <button
              type="button"
              onClick={handlePickFiles}
              disabled={uploading}
              className="group flex aspect-square flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-line text-paper-muted transition-colors hover:border-accent hover:text-paper disabled:cursor-not-allowed disabled:opacity-60"
            >
              {uploading ? (
                <Loader2 aria-hidden className="h-5 w-5 animate-spin text-accent" />
              ) : (
                <ImagePlus aria-hidden className="h-5 w-5" />
              )}
              <span className="text-[11px]">
                {uploading ? "Uploading…" : "Add photo"}
              </span>
            </button>
          ) : null}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          className="hidden"
          onChange={handleFilesSelected}
        />

        {photoError ? (
          <p role="alert" className="field-error mt-2">
            {photoError}
          </p>
        ) : (
          <p className="mt-2 text-xs text-paper-muted">
            JPG, PNG or WEBP · up to 5 MB each · {photos.length}/{MAX_PHOTOS}
          </p>
        )}
      </div>

      {error ? <p className="text-sm font-medium text-danger">{error}</p> : null}

      <div className="flex items-center justify-end">
        <Button type="submit" loading={saving} disabled={uploading}>
          Publish product <ArrowRight aria-hidden className="h-4 w-4" />
        </Button>
      </div>
    </form>
  );
}
