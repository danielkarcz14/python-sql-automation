CREATE TRIGGER trg_automaticka_aktualizace_surovin
ON polozky_objednavky
AFTER INSERT
AS
BEGIN
    DECLARE @orderCursor CURSOR;
    DECLARE @id_produktu VARCHAR(20);

    -- Declare a cursor to iterate over all unique product codes in the newly inserted orders
    SET @orderCursor = CURSOR FOR
        SELECT DISTINCT id_produktu
        FROM inserted;

    -- Open the cursor
    OPEN @orderCursor;

    -- Fetch the first product code
    FETCH NEXT FROM @orderCursor INTO @id_produktu;

    -- Loop through all product codes
    WHILE @@FETCH_STATUS = 0
    BEGIN
        -- Execute the stored procedure for the current product code
        EXEC aktualizovat_mnozstvi_surovin @p_id_produktu = @id_produktu;

        -- Fetch the next product code
        FETCH NEXT FROM @orderCursor INTO @id_produktu;
    END

    -- Close the cursor
    CLOSE @orderCursor;

    -- Deallocate the cursor
    DEALLOCATE @orderCursor;
END;
