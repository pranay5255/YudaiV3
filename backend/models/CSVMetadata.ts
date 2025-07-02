import { z } from 'zod';

export const CSVMetadataSchema = z.object({
  filename: z.string(),
  schema: z.record(z.string()),
  rowCount: z.number().int().nonnegative(),
  columnCount: z.number().int().nonnegative(),
});

export type CSVMetadata = z.infer<typeof CSVMetadataSchema>;
